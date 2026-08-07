import java.nio.file.*;
import java.util.*;
public class ReadTest {
  public static void main(String[] args) throws Exception {
    var p = Paths.get("C:\\Users\\ASUSD\\Desktop\\Wathiq_code\\tools\\elasticsearch-9.3.3\\jdk\\conf\\security\\java.security");
    System.out.println("exists=" + Files.exists(p));
    System.out.println("size=" + Files.size(p));
    System.out.println("firstLine=" + Files.readAllLines(p).get(0));
  }
}
