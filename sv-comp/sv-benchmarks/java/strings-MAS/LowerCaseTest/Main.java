import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {
    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        test(a1);
    }

    public static void test(String s1) {
        if (s1.toLowerCase().equals("helloworld")) {
            System.out.println("s1.toLowerCase() equals \"hello world!\"");
        } else {
            System.out.println("s1.toLowerCase() does not equal \"hello world!\"");
        }
    }
}
