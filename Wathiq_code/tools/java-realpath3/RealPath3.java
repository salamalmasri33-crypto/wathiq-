import java.nio.file.*;
public class RealPath3 {
  public static void main(String[] args) throws Exception {
    System.out.println(Paths.get("C:\\Windows\\System32\\notepad.exe").toRealPath());
  }
}
