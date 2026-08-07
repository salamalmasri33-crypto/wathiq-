import java.nio.file.*;
public class RealPathTest {
  public static void main(String[] args) throws Exception {
    System.out.println(Paths.get("C:\\Users\\ASUSD\\Desktop\\Wathiq_code\\tools\\elasticsearch-9.3.3\\jdk\\conf\\security\\java.security").toRealPath());
  }
}
